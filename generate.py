import sys

from crossword import *


class CrosswordCreator():

    def __init__(self, crossword):
        """
        Create new CSP crossword generate.
        """
        self.crossword = crossword
        self.domains = {
            var: self.crossword.words.copy()
            for var in self.crossword.variables
        }

    def letter_grid(self, assignment):
        """
        Return 2D array representing a given assignment.
        """
        letters = [
            [None for _ in range(self.crossword.width)]
            for _ in range(self.crossword.height)
        ]
        for variable, word in assignment.items():
            direction = variable.direction
            for k in range(len(word)):
                i = variable.i + (k if direction == Variable.DOWN else 0)
                j = variable.j + (k if direction == Variable.ACROSS else 0)
                letters[i][j] = word[k]
        return letters

    def print(self, assignment):
        """
        Print crossword assignment to the terminal.
        """
        letters = self.letter_grid(assignment)
        for i in range(self.crossword.height):
            for j in range(self.crossword.width):
                if self.crossword.structure[i][j]:
                    print(letters[i][j] or " ", end="")
                else:
                    print("█", end="")
            print()

    def save(self, assignment, filename):
        """
        Save crossword assignment to an image file.
        """
        from PIL import Image, ImageDraw, ImageFont
        cell_size = 100
        cell_border = 2
        interior_size = cell_size - 2 * cell_border
        letters = self.letter_grid(assignment)

        # Create a blank canvas
        img = Image.new(
            "RGBA",
            (self.crossword.width * cell_size,
             self.crossword.height * cell_size),
            "black"
        )
        font = ImageFont.truetype("assets/fonts/OpenSans-Regular.ttf", 80)
        draw = ImageDraw.Draw(img)

        for i in range(self.crossword.height):
            for j in range(self.crossword.width):

                rect = [
                    (j * cell_size + cell_border,
                     i * cell_size + cell_border),
                    ((j + 1) * cell_size - cell_border,
                     (i + 1) * cell_size - cell_border)
                ]
                if self.crossword.structure[i][j]:
                    draw.rectangle(rect, fill="white")
                    if letters[i][j]:
                        _, _, w, h = draw.textbbox((0, 0), letters[i][j], font=font)
                        draw.text(
                            (rect[0][0] + ((interior_size - w) / 2),
                             rect[0][1] + ((interior_size - h) / 2) - 10),
                            letters[i][j], fill="black", font=font
                        )

        img.save(filename)

    def solve(self):
        """
        Enforce node and arc consistency, and then solve the CSP.
        """
        self.enforce_node_consistency()
        self.ac3()
        return self.backtrack(dict())

    def enforce_node_consistency(self):
        """
        Update `self.domains` such that each variable is node-consistent.
        (Remove any values that are inconsistent with a variable's unary
        constraints; in this case, the length of the word.)
        """
        for var in self.domains:
            to_remove = set()
            for word in self.domains[var]:
                if len(word) != var.length:
                    to_remove.add(word)
            self.domains[var] -= to_remove

    def revise(self, x, y):
        """
        Make variable `x` arc consistent with variable `y`.
        Remove values from `self.domains[x]` that have no support in `self.domains[y]`.
        Return True if a revision was made; False otherwise.
        """
        revised = False
        overlap = self.crossword.overlaps[x, y]
        if overlap is None:
            return False  # aucune contrainte binaire entre x et y

        i, j = overlap
        to_remove = set()

        for xval in self.domains[x]:
            # xval est supporté si au moins un yval du domaine de y
            # matche la contrainte d'overlap.
            supported = False
            for yval in self.domains[y]:
                if xval[i] == yval[j]:
                    supported = True
                    break
            if not supported:
                to_remove.add(xval)

        if to_remove:
            self.domains[x] -= to_remove
            revised = True

        return revised


    def ac3(self, arcs=None):
        """
        Enforce arc consistency using the AC-3 algorithm.
        If arcs is None, start with all arcs in the problem.
        Return False if any domain becomes empty; otherwise True.
        """
        # file d'arcs à traiter
        if arcs is not None:
            queue = list(arcs)
        else:
            queue = []
            for x in self.crossword.variables:
                for y in self.crossword.neighbors(x):
                    queue.append((x, y))

        while queue:
            x, y = queue.pop(0)
            if self.revise(x, y):
                if len(self.domains[x]) == 0:
                    return False
                # si on a modifié le domaine de x, tous ses autres voisins
                # (sauf y) doivent être re-vérifiés
                for z in self.crossword.neighbors(x) - {y}:
                    queue.append((z, x))
        return True

    def assignment_complete(self, assignment):
        """
        Return True if `assignment` assigns a value to each crossword variable.
        """
        return len(assignment) == len(self.crossword.variables)


    def consistent(self, assignment):
        """
        Return True if `assignment` is consistent:
        - valeurs de bonne longueur
        - toutes les valeurs distinctes
        - pas de conflit aux overlaps entre voisins assignés
        """
        # 1) bonnes longueurs
        for var, word in assignment.items():
            if len(word) != var.length:
                return False

        # 2) unicité des mots
        values = list(assignment.values())
        if len(values) != len(set(values)):
            return False

        # 3) cohérence des overlaps
        for var, word in assignment.items():
            for neighbor in self.crossword.neighbors(var):
                if neighbor in assignment:
                    overlap = self.crossword.overlaps[var, neighbor]
                    if overlap is None:
                        continue
                    i, j = overlap
                    if word[i] != assignment[neighbor][j]:
                        return False

        return True

    def order_domain_values(self, var, assignment):
        """
        Return the domain values for `var` ordered by the least-constraining value:
        i.e., the value that rules out the fewest values among neighbors' domains.
        Only consider neighbors that are not yet assigned.
        """
        def conflicts_count(val):
            count = 0
            for nb in self.crossword.neighbors(var):
                if nb in assignment:
                    continue
                overlap = self.crossword.overlaps[var, nb]
                if overlap is None:
                    continue
                i, j = overlap
                # pour chaque valeur possible chez le voisin,
                # compter celles qui seraient éliminées
                for nb_val in self.domains[nb]:
                    if val[i] != nb_val[j]:
                        count += 1
            return count

        # trier par nombre de conflits croissant
        return sorted(list(self.domains[var]), key=conflicts_count)


    def select_unassigned_variable(self, assignment):
        """
        Return an unassigned variable not already part of `assignment`.
        Heuristics:
        - Minimum Remaining Values (MRV): variable avec le moins de valeurs possibles
        - Degree heuristic (en cas d'égalité) : variable avec le plus de voisins
        """
        unassigned = [v for v in self.crossword.variables if v not in assignment]

        # Trier d'abord par taille du domaine (croissant), puis par degré (décroissant)
        return min(
            unassigned,
            key=lambda var: (len(self.domains[var]), -len(self.crossword.neighbors(var)))
        )


    def backtrack(self, assignment):
        """
        Backtracking search:
        - si complet, renvoyer l'assignation
        - sinon, choisir une variable non assignée (MRV+degree)
        - essayer les valeurs dans l'ordre LCV
        - vérifier la consistance; si ok, continuer récursivement
        - sinon backtrack
        """
        if self.assignment_complete(assignment):
            return assignment

        var = self.select_unassigned_variable(assignment)

        for value in self.order_domain_values(var, assignment):
            new_assignment = assignment.copy()
            new_assignment[var] = value

            if self.consistent(new_assignment):
                # Optionnel: on peut faire un peu d'inférence en lançant AC3
                # sur arcs impactés pour accélérer (autorisé par la spec).
                # Pour rester simple et sûr, on n'infère pas ici.
                result = self.backtrack(new_assignment)
                if result is not None:
                    return result

        return None



def main():

    # Check usage
    if len(sys.argv) not in [3, 4]:
        sys.exit("Usage: python generate.py structure words [output]")

    # Parse command-line arguments
    structure = sys.argv[1]
    words = sys.argv[2]
    output = sys.argv[3] if len(sys.argv) == 4 else None

    # Generate crossword
    crossword = Crossword(structure, words)
    creator = CrosswordCreator(crossword)
    assignment = creator.solve()

    # Print result
    if assignment is None:
        print("No solution.")
    else:
        creator.print(assignment)
        if output:
            creator.save(assignment, output)


if __name__ == "__main__":
    main()
